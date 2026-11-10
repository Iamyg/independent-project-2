import scala.math.Ordered.orderingToOrdered
import org.hkust.BasedProcessFunctions.RelationFKProcessFunction
import org.hkust.RelationType.Payload
import java.util.Date
import scala.util.matching.Regex
class QcustomerProcessFunction extends RelationFKProcessFunction[Any]("customer",Array("CUSTKEY"),Array("CUSTKEY"),false) {
override def isValid(value: Payload): Boolean = {
   if( (value("C_MKTSEGMENT").asInstanceOf[String]=="AUTOMOBILE") ){
   true}else{
   false}
}
}
